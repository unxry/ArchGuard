package controller;
public class HttpController {
    // BENCHMARK_DEPENDENCIES
    public String respond(String content) { return "HTTP/1.1 200 OK body=" + content; }
}
