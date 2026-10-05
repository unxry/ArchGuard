import { OrderService } from "../services/OrderService";
@Controller("PRIVATE_DECORATOR_ARGUMENT")
export class UserController { static run() { OrderService.run(); } }
