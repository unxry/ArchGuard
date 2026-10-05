import { OrderPort } from './OrderPort';
export class Order {
    // BENCHMARK_DEPENDENCIES
    private port!: OrderPort; save(id: number) { this.port.save(id); }
}
