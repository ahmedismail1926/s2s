// Offline check: drives onToolCall with a mock session (no jambonz, no Gemini).
const {onToolCall} = require('./lib/routes/kb-shared');
const sent = [];
const session = {call_sid: 'offline-test', locals: {logger: {info() {}, error() {}}},
  sendToolOutput: (id, payload) => sent.push({id, payload})};
onToolCall(session, {tool_call_id: 't1', function_calls: [{name: 'search_kb', id: 'c1', args: {query: 'مواعيد العمل'}}]})
  .then(() => { console.log(JSON.stringify(sent[0]).slice(0, 300)); });
