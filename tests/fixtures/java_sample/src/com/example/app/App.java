package com.example.app;

import com.example.model.*;
import com.example.util.Formatter;
import com.example.util.Helper;
import static com.example.util.Helper.shout;

/** Where the JVM starts this project. */
public class App {

    private final Formatter formatter;

    private int runs;

    public App(Formatter formatter) {
        this.formatter = formatter;
    }

    public static void main(String[] args) {
        App app = new App(new Formatter());
        app.start();
    }

    void start() {
        this.tally();
        formatter.wrap("hello");
        Helper.shout("direct");
        shout("static import");
        mystery.compute();
        super.toString();
    }

    private void tally() {
        runs = runs + 1;
    }

    static class Launcher {

        void launch() {
        }
    }
}
