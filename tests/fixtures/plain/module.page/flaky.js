const response = await fetch(new URL("./flaky.json", import.meta.url));
const { week, suites } = await response.json();

const container = document.getElementById("suites");
const most = Math.max(
  ...suites.flatMap((suite) => suite.tests.map((test) => test.retries)),
);
let total = 0;
for (const suite of suites) {
  const section = document.createElement("section");
  section.className = "suite";
  const heading = document.createElement("h2");
  heading.textContent = suite.name;
  const list = document.createElement("ol");
  for (const test of suite.tests) {
    total += test.retries;
    const item = document.createElement("li");
    item.className = "test";
    const name = document.createElement("span");
    name.className = "name";
    name.textContent = test.name;
    const count = document.createElement("span");
    count.className = `count ${test.retries >= 10 ? "hot" : test.retries >= 5 ? "warm" : ""}`;
    count.textContent = test.retries;
    const meter = document.createElement("div");
    meter.className = "meter";
    const fill = document.createElement("span");
    fill.style.width = `${(test.retries / most) * 100}%`;
    meter.append(fill);
    item.append(name, count, meter);
    list.append(item);
  }
  section.append(heading, list);
  container.append(section);
}
document.getElementById("summary").textContent =
  `${total} retries in the week of ${week}`;
container.setAttribute("aria-busy", "false");
