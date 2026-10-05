package service;
public class PostingCoordinator {
    domain.CommitPort reference0;
    domain.AuditPort reference1;
    domain.EventPort reference2;
    // BENCHMARK_DEPENDENCIES
    public void post(int id) { reference0.commit(id); reference1.record(id); reference2.publish(id); }

}
