package com.example.model;

/** A closed set of shapes the catalog knows how to describe. */
public sealed interface Shape permits Circle, Square {

    double area();

    default String describe() {
        return "a shape";
    }
}

record Circle(double radius) implements Shape {

    public double area() {
        return Math.PI * radius * radius;
    }
}

record Square(double side) implements Shape {

    public double area() {
        return side * side;
    }
}
