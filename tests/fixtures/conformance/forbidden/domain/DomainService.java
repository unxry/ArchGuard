package shop.domain;
import shop.infrastructure.InfrastructureAdapter;
public class DomainService {
    public void run() { InfrastructureAdapter.save(); }
}
