import { Worker1 } from '../graph/Worker1';
import { Worker2 } from '../graph/Worker2';
import { Worker3 } from '../graph/Worker3';
import { Worker4 } from '../graph/Worker4';
import { Worker5 } from '../graph/Worker5';
export class Dispatcher {
    reference0!: Worker1;
    reference1!: Worker2;
    reference2!: Worker3;
    reference3!: Worker4;
    reference4!: Worker5;
    // BENCHMARK_DEPENDENCIES
    operation0(): number { return 0; }
    operation1(): number { return 1; }
    operation2(): number { return 2; }

}
