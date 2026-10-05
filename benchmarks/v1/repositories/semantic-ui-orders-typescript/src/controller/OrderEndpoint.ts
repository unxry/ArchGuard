import { ApprovalService } from '../service/ApprovalService';
export class OrderEndpoint {
    reference0!: ApprovalService;
    // BENCHMARK_DEPENDENCIES
    handle(quantity: number): string { if (!this.valid(quantity)) { return "invalid"; } return this.reference0.approve(this.map(quantity)); } private valid(value: number): boolean { return value >= 0; } private map(value: number): number { return value; }

}
