Encoding: nested JSON element tree. Return one JSON object for the section root.
Every element has exactly type (tag string), props (attribute object), and
children (ordered array of element objects or literal text strings). Attribute
values are strings or booleans; true emits the attribute and false omits it.
The host escapes text and attribute values, then renders the same HTML fragment.
Example artifact:

{"type":"section","props":{"id":"example"},"children":[{"type":"p","props":{},"children":["Current status"]}]}
