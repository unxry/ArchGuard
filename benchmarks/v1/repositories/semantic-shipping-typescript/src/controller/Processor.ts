export class Processor {
    // BENCHMARK_DEPENDENCIES
    submit(text: string): string { const weight = Number(text); const price = weight > 20 ? weight * 7 : weight * 3; return "INSERT INTO freight(price) VALUES (" + price + ")"; }

}
