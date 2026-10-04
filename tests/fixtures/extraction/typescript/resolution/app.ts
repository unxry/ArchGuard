function hit() {} function run(hit: () => void) { hit(); service.execute(); } function plain() { hit(); } class Tools { static ping(value: number) {} static run() { this.ping(1); } }
