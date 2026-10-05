import { ShippingService } from '../service/ShippingService';
export class RequestEndpoint {
    reference0!: ShippingService;
    // BENCHMARK_DEPENDENCIES
    handle(weight: number): number { const value = this.map(weight); if (!this.valid(value)) { return -1; } return this.reference0.route(value); } private map(value: number): number { return value; } private valid(value: number): boolean { return value >= 0; }

}
