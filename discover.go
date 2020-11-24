package main

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"

	"github.com/getsentry/sentry-go"
)

// Data is an array of events but not full events. It's an event w/ Id and Project name, like metadata
type Discover struct {
	Data []map[string]interface{} `json:"data"`
}

// IdProjectPair
// EventIdProjectPair
type EventMini struct {
	Id      string
	Project string
}

func (d Discover) latestEventList() []EventMini {
	org := os.Getenv("ORG")
	n := 15

	endpoint := fmt.Sprint("https://sentry.io/api/0/organizations/", org, "/eventsv2/?statsPeriod=24h&project=5422148&project=5427415&field=title&field=event.type&field=project&field=user.display&field=timestamp&sort=-timestamp&per_page=", n, "&query=")
	request, _ := http.NewRequest("GET", endpoint, nil)
	request.Header.Set("content-type", "application/json")
	request.Header.Set("Authorization", fmt.Sprint("Bearer ", os.Getenv("SENTRY_AUTH_TOKEN")))

	var httpClient = &http.Client{}
	response, requestErr := httpClient.Do(request)
	if requestErr != nil {
		sentry.CaptureException(requestErr)
		log.Fatal(requestErr)
	}
	body, errResponse := ioutil.ReadAll(response.Body)
	if errResponse != nil {
		sentry.CaptureException(errResponse)
		log.Fatal(errResponse)
	}

	json.Unmarshal(body, &d)
	eventList := d.Data

	var eventMinis []EventMini
	for _, e := range eventList {
		eventMini := EventMini{e["id"].(string), e["project"].(string)}
		eventMinis = append(eventMinis, eventMini)
	}
	return eventMinis
}
