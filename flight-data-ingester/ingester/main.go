package main

import (
	"context"
	"os"
	"os/signal"
	"strings"

	greptime "github.com/GreptimeTeam/greptimedb-ingester-go"

	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"syscall"
	"time"
)

var (
	ICAO_AIRPORT_CODE string
	numFlights        = 10
)

var greptimeClient *greptime.Client

func init() {
	ICAO_AIRPORT_CODE = os.Getenv("ICAO_AIRPORT_CODE")
	if ICAO_AIRPORT_CODE == "" {
		log.Fatalf("❌ ICAO_AIRPORT_CODE environment variable is not set")
	}

	cfg := greptime.NewConfig("greptimedb").
		WithDatabase("public").
		WithAuth(os.Getenv("GREPTIME_USERNAME"), os.Getenv("GREPTIME_PASSWORD"))

	var err error
	greptimeClient, err = greptime.NewClient(cfg)
	if err != nil {
		log.Fatalf("❌ Failed to create GreptimeDB client: %v", err)
	}

	fmt.Println("📌 GreptimeDB client initialized successfully")
}

func main() {

	fmt.Println("📌 starting flight-data-ingester demo")

	trackFlights, err := SelectLiveFlights(ICAO_AIRPORT_CODE, numFlights)
	if err != nil {
		log.Fatalf("❌ could not select live flights %+v\n", err)
	}

	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGTERM)

	for {
		select {
		case <-ticker.C:
			statesResponse, err := GetFlightState(trackFlights)
			if err != nil {
				fmt.Printf("❌ could not get flight state: %+v\n", err)
				continue
			}

			flightMetrics := statesResponse.ToFlightMetrics()

			resp, err := greptimeClient.WriteObject(context.Background(), flightMetrics)
			if err != nil {
				fmt.Printf("❌ could not write to greptime: %+v\n", err)
				continue
			}
			log.Printf("inserted rows: %d\n", resp.GetAffectedRows().GetValue())

		case <-done:
			fmt.Println("Received termination signal. Shutting down...")
			return
		}
	}
}

func GetFlightState(flight []Flight) (*StateResponse, error) {
	icaoCsv := ""
	icaos := make([]string, len(flight))
	for _, f := range flight {
		icaos = append(icaos, f.Icao24)
	}
	icaoCsv = strings.Join(icaos, ",")
	url := fmt.Sprintf("https://opensky-network.org/api/states/all?icao24=%s", icaoCsv)

	req, err := OpenSkyReq(url)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %v", err)
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error making request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("unexpected status code: %d, and error reading response body: %v", resp.StatusCode, err)
		}
		bodyString := string(bodyBytes)
		return nil, fmt.Errorf("unexpected status code: %d : %s", resp.StatusCode, bodyString)
	}

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading response body: %v", err)
	}

	var statesResponse StateResponse
	err = json.Unmarshal(bodyBytes, &statesResponse)
	if err != nil {
		return nil, fmt.Errorf("error decoding response: %v - response body: %s", err, string(bodyBytes))
	}

	if len(statesResponse.States) == 0 {
		return nil, fmt.Errorf("no aircraft data found for the given flights")
	}

	fmt.Printf("selected: state data for %+v flights\n", len(statesResponse.States))
	return &statesResponse, nil
}

func SelectLiveFlights(airportCode string, num int) ([]Flight, error) {
	endTime := time.Now().Unix()
	startTime := endTime - 60*30 // all flights leaving in last 30 minutes

	url := fmt.Sprintf("https://opensky-network.org/api/flights/departure?begin=%d&end=%d&airport=%s", startTime, endTime, airportCode)

	req, err := OpenSkyReq(url)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %v", err)
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("error making request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		bodyBytes, err := io.ReadAll(resp.Body)
		if err != nil {
			return nil, fmt.Errorf("unexpected status code: %d, and error reading response body: %v", resp.StatusCode, err)
		}
		bodyString := string(bodyBytes)
		return nil, fmt.Errorf("unexpected status code: %d : %s", resp.StatusCode, bodyString)
	}

	var flights []Flight

	if err := json.NewDecoder(resp.Body).Decode(&flights); err != nil {
		return nil, fmt.Errorf("error decoding response: %+v", err)
	}

	if len(flights) == 0 {
		return nil, fmt.Errorf("no flights found in the last 10 minutes")
	}

	if num > len(flights) {
		num = len(flights)
	}

	return flights[:num], nil

}

func OpenSkyReq(url string) (*http.Request, error) {
	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %w", err)
	}

	// Add basic auth if credentials are present
	username := os.Getenv("OPENSKY_USERNAME")
	password := os.Getenv("OPENSKY_PASSWORD")
	if username != "" && password != "" {
		req.SetBasicAuth(username, password)
	}
	return req, nil
}
