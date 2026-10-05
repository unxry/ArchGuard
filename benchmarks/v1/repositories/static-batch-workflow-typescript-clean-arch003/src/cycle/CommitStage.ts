import { ReadStage } from './ReadStage';
export class CommitStage {
    benchmarkDependency!: ReadStage;
    step(): number { return 7; }

}
