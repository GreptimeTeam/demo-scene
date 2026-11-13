package main

import (
	"context"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"
)

type roundTripFunc func(*http.Request) (*http.Response, error)

func (f roundTripFunc) RoundTrip(r *http.Request) (*http.Response, error) { return f(r) }

func TestBounds(t *testing.T) {
	for _, raw := range []string{"", "1,2,3", "NaN,0,1,1", "-91,0,1,1", "1,0,0,1", "0,2,1,1"} {
		if _, err := parseBounds(raw); err == nil {
			t.Errorf("accepted invalid bounds %q", raw)
		}
	}
	bounds, err := parseBounds("37, -123,38,-121")
	if err != nil || bounds.Get("lomin") != "-123" || bounds.Get("lamax") != "38" {
		t.Fatalf("bounds: %v, %v", bounds, err)
	}
}

func TestOAuthRefreshAndStateRequest(t *testing.T) {
	tokens, requests := 0, 0
	client := &openSkyClient{clientID: "demo", clientSecret: "secret"}
	client.httpClient = &http.Client{Transport: roundTripFunc(func(r *http.Request) (*http.Response, error) {
		body := `{"time":1,"states":[]}`
		if r.URL.String() == tokenURL {
			tokens++
			if err := r.ParseForm(); err != nil {
				t.Fatal(err)
			}
			if r.Form.Get("client_id") != "demo" || r.Form.Get("client_secret") != "secret" || r.Form.Get("grant_type") != "client_credentials" {
				t.Fatal("invalid credentials form")
			}
			body = `{"access_token":"token","expires_in":1800}`
		} else {
			requests++
			if r.Header.Get("Authorization") != "Bearer token" || r.URL.Query().Get("lamin") != "37" {
				t.Fatalf("invalid state request: %v", r)
			}
		}
		return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body)), Header: make(http.Header)}, nil
	})}
	bounds, _ := parseBounds("37,-123,38,-121")
	for i := 0; i < 2; i++ {
		if _, err := client.states(context.Background(), bounds); err != nil {
			t.Fatal(err)
		}
	}
	if tokens != 1 || requests != 2 {
		t.Fatalf("token cache not used: tokens=%d requests=%d", tokens, requests)
	}
	client.expiresAt = time.Now().Add(-time.Second)
	if _, err := client.states(context.Background(), bounds); err != nil {
		t.Fatal(err)
	}
	if tokens != 2 {
		t.Fatal("expired token not refreshed")
	}
}
