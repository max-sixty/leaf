// markdown-it-task-lists/index.js installs one core rule and reads these options.
// The package supplies no declarations; markdown-it owns the plugin interface.
declare module "markdown-it-task-lists" {
  import type MarkdownIt from "markdown-it";
  interface TaskListOptions {
    enabled?: boolean;
    label?: boolean;
    labelAfter?: boolean;
  }
  const taskLists: (
    md: ReturnType<typeof MarkdownIt>,
    options?: TaskListOptions,
  ) => void;
  export default taskLists;
}
