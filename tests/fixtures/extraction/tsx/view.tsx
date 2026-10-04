import React from "react"; export interface Props { title: string; } export function Card(props: Props) { return <section><h1>{props.title}</h1><span /></section>; }
