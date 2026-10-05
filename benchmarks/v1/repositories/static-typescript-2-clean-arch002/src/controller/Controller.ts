import { Repository } from '../repository/Repository';
import { Service } from '../service/Service';
export class Controller {
    serviceDependency!: Service;

    benchmarkDependency!: Repository;
}
