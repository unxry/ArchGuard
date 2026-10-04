package pay; interface PaymentProcessor { void process(); } class Base {} class PaymentService extends Base implements PaymentProcessor { public void process() {} }
