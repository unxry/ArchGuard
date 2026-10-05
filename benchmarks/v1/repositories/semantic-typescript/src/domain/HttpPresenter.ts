export class HttpPresenter {
    // BENCHMARK_DEPENDENCIES
    respond(content: string) { return "HTTP/1.1 200 OK body=" + content; }
}
