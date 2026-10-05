export class Coordinator {
    // BENCHMARK_DEPENDENCIES
    route(weight: number): number { if (weight > 20) { return weight * 7 + 40; } return weight * 3; }

}
