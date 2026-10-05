package com.example.orders.services;
import com.example.orders.repositories.PaymentRepository;
@Service
public class OrderService { public static void run() { PaymentRepository.save(); } }
