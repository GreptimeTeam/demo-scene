package main

import (
	"context"
	"os"
	"os/signal"

	greptime "github.com/GreptimeTeam/greptimedb-ingester-go"

	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"syscall"
	"time"
)

var greptimeClient *greptime.Client

func init() {
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
	
	fmt.Printf("📌 starting flight-data-ingester demo" , %+v\n )
	
	flight, err := SelectLiveFlight()
	if err != nil {
		log.Fatalf("❌ could not select live flight %+v\n", err)
	}

	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()

	// Create a done channel to signal when to stop the loop
	done := make(chan os.Signal, 1)
	signal.Notify(done, os.Interrupt, syscall.SIGTERM)

	for {
		select {
		case <-ticker.C:
			stateData, err := GetFlightState(flight)
			if err != nil {
				log.Printf("❌ could not get flight state: %+v\n", err)
				continue
			}

			resp, err := greptimeClient.WriteObject(context.Background(), []FlightMetric{stateData.ToFlightMetric()})
			if err != nil {
				fmt.Printf("❌ could not write to greptime: %+v\n", err)
				continue
			}
			log.Printf("affected rows: %d\n", resp.GetAffectedRows().GetValue())

			fmt.Printf("📌 State Data: %+v\n", stateData)
		case <-done:
			fmt.Println("Received termination signal. Shutting down...")
			return
		}
	}
}

func GetFlightState(flight *Flight) (*StateData, error) {
	url := fmt.Sprintf("https://opensky-network.org/api/states/all?icao24=%s", flight.Icao24)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(url)
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
	fmt.Printf("📌 Response body %s\n", string(bodyBytes))

	var stateResponse StateResponse
	err = json.Unmarshal(bodyBytes, &stateResponse)
	if err != nil {
		return nil, fmt.Errorf("error decoding response: %v - response body: %s", err, string(bodyBytes))
	}

	if len(stateResponse.States) == 0 {
		return nil, fmt.Errorf("no aircraft data found for the given flight")
	}

	stateData := stateResponse.ToStateData()
	if stateData == nil {
		return nil, fmt.Errorf("invalid state data format")
	}

	return stateData, nil
}

func SelectLiveFlight() (*Flight, error) {
	endTime := time.Now().Unix()
	startTime := endTime - 600 // 10 minutes ago

	url := fmt.Sprintf("https://opensky-network.org/api/flights/departure?begin=%d&end=%d&airport=KSFO", startTime, endTime)

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Get(url)
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
		return nil, fmt.Errorf("error decoding response: %v", err)
	}

	if len(flights) == 0 {
		return nil, fmt.Errorf("no flights found in the last 10 minutes")
	}

	// Select the most recent flight
	selectedFlight := &flights[0]
	for i := 1; i < len(flights); i++ {
		if flights[i].FirstSeen > selectedFlight.FirstSeen {
			selectedFlight = &flights[i]
		}
	}

	fmt.Printf("📌 %+v\n", selectedFlight)

	return selectedFlight, nil
}
