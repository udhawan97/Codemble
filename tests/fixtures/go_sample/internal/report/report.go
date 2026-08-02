package report

import (
	"fmt"
	"strings"

	"example.com/sample/internal/store"
)

func Render(s *store.Store) string {
	defer fmt.Println("rendered")
	return strings.Join(collect(s), "\n")
}

func collect(s *store.Store) []string {
	out := make(chan string, 1)
	go emit(out, s.Count())
	value := <-out
	return Map([]string{value}, decorate)
}

func Map[T any, U any](in []T, transform func(T) U) []U {
	out := make([]U, 0, len(in))
	for _, item := range in {
		out = append(out, transform(item))
	}
	return out
}

func decorate(text string) string {
	return "- " + text
}

func emit(out chan string, count int) {
	out <- fmt.Sprintf("%d entries", count)
}

func headings() []string {
	return Map[string, string]([]string{"one"}, decorate)
}

func first[T any](in []T) []T {
	return in
}

func titles() []string {
	return first[string]([]string{"two"})
}
