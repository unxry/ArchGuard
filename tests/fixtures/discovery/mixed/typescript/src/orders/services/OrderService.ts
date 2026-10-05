import { PaymentRepository } from "../repositories/PaymentRepository";
@Injectable()
export class OrderService { static run() { PaymentRepository.save(); } }
