package com.example.model;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.List;

public class Catalog {

    public enum Status {
        DRAFT,
        PUBLISHED
    }

    private final List<Shape> shapes = new ArrayList<>();

    @Deprecated
    public List<String> names() {
        return shapes.stream().map(shape -> shape.describe()).toList();
    }

    public String firstLine(String text) throws IOException {
        try (BufferedReader reader = new BufferedReader(new StringReader(text))) {
            return reader.readLine();
        }
    }

    static final class Index {

        int size() {
            return 0;
        }
    }
}
