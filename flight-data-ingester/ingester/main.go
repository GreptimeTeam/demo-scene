package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	greptime "github.com/GreptimeTeam/greptimedb-ingester-go"
)

const tokenURL = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"

type openSkyClient struct {
	httpClient             *http.Client
	clientID, clientSecret string
	token                  string
	expiresAt              time.Time
}

func (c *openSkyClient) accessToken(ctx context.Context) (string, error) {
	if c.token != "" && time.Now().Before(c.expiresAt) {
		return c.token, nil
	}
	form := url.Values{"grant_type": {"client_credentials"}, "client_id": {c.clientID}, "client_secret": {c.clientSecret}}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, tokenURL, strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("OpenSky token request: HTTP %d", resp.StatusCode)
	}
	var result struct {
		AccessToken string `json:"access_token"`
		ExpiresIn   int    `json:"expires_in"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", err
	}
	if result.AccessToken == "" || result.ExpiresIn <= 0 {
		return "", fmt.Errorf("OpenSky returned an invalid token response")
	}
	c.token = result.AccessToken
	c.expiresAt = time.Now().Add(time.Duration(result.ExpiresIn)*time.Second - 30*time.Second)
	return c.token, nil
}

func (c *openSkyClient) states(ctx context.Context, bounds url.Values) (*StateResponse, error) {
	token, err := c.accessToken(ctx)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, "https://opensky-network.org/api/states/all?"+bounds.Encode(), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusUnauthorized {
		c.token = ""
	}
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(io.LimitReader(resp.Body, 1024))
		return nil, fmt.Errorf("OpenSky states: HTTP %d: %s", resp.StatusCode, body)
	}
	var result StateResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, err
	}
	return &result, nil
}

func parseBounds(raw string) (url.Values, error) {
	parts := strings.Split(raw, ",")
	if len(parts) != 4 {
		return nil, fmt.Errorf("OPENSKY_BBOX must contain lamin,lomin,lamax,lomax")
	}
	values := make([]float64, 4)
	bounds := url.Values{}
	for i, key := range []string{"lamin", "lomin", "lamax", "lomax"} {
		value, err := strconv.ParseFloat(strings.TrimSpace(parts[i]), 64)
		limit := 90.0
		if i%2 == 1 {
			limit = 180
		}
		if err != nil || !(value >= -limit && value <= limit) {
			return nil, fmt.Errorf("invalid %s in OPENSKY_BBOX", key)
		}
		values[i] = value
		bounds.Set(key, strconv.FormatFloat(value, 'f', -1, 64))
	}
	if values[0] >= values[2] || values[1] >= values[3] {
		return nil, fmt.Errorf("OPENSKY_BBOX minimums must be smaller than maximums")
	}
	return bounds, nil
}

func main() {
	bounds, err := parseBounds(os.Getenv("OPENSKY_BBOX"))
	if err != nil {
		log.Fatal(err)
	}
	client := &openSkyClient{
		httpClient: &http.Client{Timeout: 20 * time.Second},
		clientID:   os.Getenv("OPENSKY_CLIENT_ID"), clientSecret: os.Getenv("OPENSKY_CLIENT_SECRET"),
	}
	if client.clientID == "" || client.clientSecret == "" {
		log.Fatal("OPENSKY_CLIENT_ID and OPENSKY_CLIENT_SECRET are required")
	}
	cfg := greptime.NewConfig("greptimedb").WithDatabase("public").WithAuth(os.Getenv("GREPTIME_USERNAME"), os.Getenv("GREPTIME_PASSWORD"))
	db, err := greptime.NewClient(cfg)
	if err != nil {
		log.Fatal(err)
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	ticker := time.NewTicker(60 * time.Second)
	defer ticker.Stop()
	for {
		states, err := client.states(ctx, bounds)
		if err != nil {
			log.Printf("Fetch states: %v", err)
		} else if rows := states.ToFlightMetrics(); len(rows) > 0 {
			resp, err := db.WriteObject(ctx, rows)
			if err != nil {
				log.Printf("Write states: %v", err)
			} else {
				log.Printf("Inserted rows: %d", resp.GetAffectedRows().GetValue())
			}
		} else {
			log.Print("No aircraft in the configured area")
		}
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}
	}
}
