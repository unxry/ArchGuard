import { AuditTransport } from '../infrastructure/AuditTransport';
export class Cart {
    benchmarkDependency!: AuditTransport;
    step(): number { return 4; }

}
