export class WorkflowEntrypoint<Env> {
  protected env: Env;

  constructor(_ctx: unknown, env: Env) {
    this.env = env;
  }
}
