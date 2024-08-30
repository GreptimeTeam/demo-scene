package main

import "time"

type FlightMetric struct {
	Icao24       string    `greptime:"tag;column:icao24;type:string"`
	Longitude    *float64  `greptime:"tag;column:longitude;type:float64"`
	Latitude     *float64  `greptime:"tag;column:latitude;type:float64"`
	Velocity     *float64  `greptime:"tag;column:velocity;type:float64"`
	BaroAltitude *float64  `greptime:"tag;column:baro_altitude;type:float64"`
	GeoAltitude  *float64  `greptime:"tag;column:geo_altitude;type:float64"`
	TimePosition *int64    `greptime:"tag;column:time_position;type:int64"`
	Timestamp    time.Time `greptime:"timestamp;column:ts;type:timestamp;precision:millisecond"`
}

func (FlightMetric) TableName() string {
	return "icao24_state"
}

type Flight struct {
	Icao24                          string `json:"icao24"`
	FirstSeen                       int64  `json:"firstSeen"`
	EstDepartureAirport             string `json:"estDepartureAirport"`
	LastSeen                        int64  `json:"lastSeen"`
	EstArrivalAirport               string `json:"estArrivalAirport"`
	CallSign                        string `json:"callsign"`
	EstDepartureTime                int64  `json:"estDepartureTime"`
	EstArrivalTime                  int64  `json:"estArrivalTime"`
	DepartureAirportCandidatesCount int    `json:"departureAirportCandidatesCount"`
	ArrivalAirportCandidatesCount   int    `json:"arrivalAirportCandidatesCount"`
}

type StateResponse struct {
	Time   int64           `json:"time"`
	States [][]interface{} `json:"states"`
}

func (sr *StateResponse) ToFlightMetrics() []FlightMetric {
	metrics := make([]FlightMetric, 0, len(sr.States))
	for _, state := range sr.States {
		if len(state) < 17 {
			continue // Skip if the state doesn't have enough elements
		}
		// check the state vector positions

		metric := FlightMetric{
			Icao24:       state[0].(string),
			Longitude:    floatToFloat64Ptr(state[5]),
			Latitude:     floatToFloat64Ptr(state[6]),
			BaroAltitude: floatToFloat64Ptr(state[7]),
			Velocity:     floatToFloat64Ptr(state[9]),
			GeoAltitude:  floatToFloat64Ptr(state[13]),
			Timestamp:    time.Unix(sr.Time, 0),
			TimePosition: floatToInt64Ptr(state[3]),
		}
		metrics = append(metrics, metric)
	}
	return metrics
}

// https://openskynetwork.github.io/opensky-api/rest.html#all-state-vectors
// StateData{
// 		Icao24:         state[0].(string),
// 		Callsign:       state[1].(string),
// 		OriginCountry:  state[2].(string),
// 		TimePosition:   floatToInt64Ptr(state[3]),
// 		LastContact:    floatToInt64(state[4]),
// 		Longitude:      floatToFloat64Ptr(state[5]),
// 		Latitude:       floatToFloat64Ptr(state[6]),
// 		BaroAltitude:   floatToFloat64Ptr(state[7]),
// 		OnGround:       state[8].(bool),
// 		Velocity:       floatToFloat64Ptr(state[9]),
// 		TrueTrack:      floatToFloat64Ptr(state[10]),
// 		VerticalRate:   floatToFloat64Ptr(state[11]),
// 		Sensors:        nil, // This field is null in the example
// 		GeoAltitude:    floatToFloat64Ptr(state[13]),
// 		Squawk:         nil, // This field is null in the example
// 		Spi:            state[15].(bool),
// 		PositionSource: floatToInt(state[16]),

func floatToInt64Ptr(v interface{}) *int64 {
	if v == nil {
		return nil
	}
	i := int64(v.(float64))
	return &i
}

func floatToFloat64Ptr(v interface{}) *float64 {
	if v == nil {
		return nil
	}
	f := v.(float64)
	return &f
}
