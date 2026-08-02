package store

import "errors"

type Writer interface {
	Save(entry string) error
}

type base struct {
	id int
}

type Store struct {
	base
	entries []string
}

var _ Writer = (*Store)(nil)

func New() *Store {
	return &Store{}
}

func (s *Store) Save(entry string) error {
	if entry == "" {
		return errors.New("empty entry")
	}
	s.entries = append(s.entries, entry)
	return nil
}

func (s Store) Count() int {
	return len(s.entries)
}

func persist(w Writer, entry string) error {
	return w.Save(entry)
}
