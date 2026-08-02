package com.example.util;

import java.util.List;

public class Formatter {

    private final String prefix;

    public Formatter() {
        this.prefix = "> ";
    }

    public String wrap(String value) {
        return prefix + value;
    }

    public String wrap(String value, int times) {
        return wrap(value);
    }

    public <T> List<String> labels(List<T> items) {
        return items.stream().map(item -> item.toString()).toList();
    }
}
