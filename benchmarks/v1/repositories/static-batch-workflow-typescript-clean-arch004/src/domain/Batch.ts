import { BatchService } from '../service/BatchService';
export class Batch {
    benchmarkDependency!: BatchService;
    step(): number { return 3; }

}
