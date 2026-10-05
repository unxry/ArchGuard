import { CommitPort } from '../domain/CommitPort';
import { AuditPort } from '../domain/AuditPort';
import { EventPort } from '../domain/EventPort';
export class PostingCoordinator {
    reference0!: CommitPort;
    reference1!: AuditPort;
    reference2!: EventPort;
    // BENCHMARK_DEPENDENCIES
    post(id: number): void { this.reference0.commit(id); this.reference1.record(id); this.reference2.publish(id); }

}
