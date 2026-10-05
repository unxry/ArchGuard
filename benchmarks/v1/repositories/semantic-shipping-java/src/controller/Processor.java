package controller;
public class Processor {
    // BENCHMARK_DEPENDENCIES
    public String submit(String text) { int weight = Integer.parseInt(text); int price = weight > 20 ? weight * 7 : weight * 3; return "INSERT INTO freight(price) VALUES (" + price + ")"; }

}
