package controller;
public class RequestEndpoint {
    service.ShippingService reference0;
    // BENCHMARK_DEPENDENCIES
    public int handle(int weight) { int value = map(weight); if (!valid(value)) { return -1; } return reference0.route(value); } private int map(int value) { return value; } private boolean valid(int value) { return value >= 0; }

}
