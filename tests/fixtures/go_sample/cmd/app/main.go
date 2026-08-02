package main

import (
	"fmt"

	"example.com/sample/internal/report"
	"example.com/sample/internal/store"
)

func main() {
	s := store.New()
	if err := s.Save("hello"); err != nil {
		fmt.Println(err)
	}
	fmt.Println(report.Render(s))
}

func Boot() *store.Store {
	return store.New()
}
