declare module "d3-force-3d" {
  export function forceX(x?: number | ((node: any) => number)): any;
  export function forceY(y?: number | ((node: any) => number)): any;
  export function forceZ(z?: number | ((node: any) => number)): any;
  export function forceManyBody(): any;
}
