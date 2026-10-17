import type { Request } from 'express';
import { Pool } from 'pg';
const pool = new Pool();
export function search(req: Request) {
  const customer = req.query.customer;
  const query = "SELECT id FROM orders WHERE customer = '" + customer + "'";
  return pool.query(query);
}
