export * from "@observablehq/plot";
// d3's number and UTC time formatters, which Plot's tip applies to a string `format`.
// lf-chart's preview applies them to an author's tip format too. The prefix keeps them
// from shadowing a name Plot may export.
export { format as d3Format, utcFormat as d3UtcFormat } from "d3";
