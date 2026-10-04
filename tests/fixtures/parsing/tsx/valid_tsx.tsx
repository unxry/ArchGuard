import React from "react";

interface Props { name: string; }

export function OrderView({ name }: Props) {
    return <section><h1>{name}</h1><input disabled={true} /></section>;
}
