/**
 * Tool definition (search_kb), tool-call handler and session handlers.
 * Replaces the weather tool of jambonz/gemini-s2s-example.
 */
const {searchKb} = require('../kb-client');
const {logEvent} = require('../calllog');

const SYSTEM_INSTRUCTION =
  'انت موظف خدمة عملاء مصري. جاوب بس من نتايج الأداة search_kb. ' +
  'لازم تنادي search_kb لكل سؤال. خلّي الرد قصير ومناسب للكلام (جملة أو جملتين). ' +
  'لو ملقيتش إجابة في النتايج قول إنك مالقيتش المعلومة دي.';

const GREETING = 'رحب بالمتصل بشكل ودود بالمصري واسأله تقدر تساعده إزاي.';

const KB_TOOL = {
  functionDeclarations: [{
    name: 'search_kb',
    description: 'Search the company knowledge base and return the top 3 passages.',
    parameters: {
      type: 'object',
      properties: {query: {type: 'string', description: 'search query in Arabic'}},
      required: ['query']
    }
  }]
};

function buildSetup(model) {
  return {
    model,
    generationConfig: {speechConfig: {voiceConfig: {prebuiltVoiceConfig: {voiceName: 'Aoede'}}}},
    systemInstruction: {parts: [{text: SYSTEM_INSTRUCTION}]},
    tools: [KB_TOOL]
  };
}

async function handleFunctionCall(fn, call_sid) {
  const {name, args, id} = fn;
  if (name !== 'search_kb') return {response: {text: 'ok'}, id};
  try {
    const {passages, kb_ms, http_ms} = await searchKb((args || {}).query || '');
    logEvent({event: 'kb_result', call_sid, query: (args || {}).query, kb_ms, kb_http_ms: http_ms, hits: passages.length});
    return {response: {output: {passages}}, id};
  } catch (err) {
    logEvent({event: 'kb_error', call_sid, error: String(err)});
    return {response: {output: {text: 'KB lookup failed.'}}, id};
  }
}

async function onToolCall(session, evt) {
  const {logger} = session.locals;
  const {function_calls, tool_call_id} = evt;
  const t_recv = Date.now();
  logEvent({event: 'tool_call_received', call_sid: session.call_sid, calls: function_calls.map((f) => ({name: f.name, args: f.args}))});
  const functionResponses = [];
  for (const fn of function_calls) functionResponses.push(await handleFunctionCall(fn, session.call_sid));
  session.sendToolOutput(tool_call_id, {toolResponse: {functionResponses}});
  logEvent({event: 'tool_response_sent', call_sid: session.call_sid, tool_handler_ms: Date.now() - t_recv});
  logger.info('search_kb tool response sent');
}

async function onFinal(session, evt) {
  session.locals.logger.info(`got actionHook: ${JSON.stringify(evt)}`);
  logEvent({event: 'action_hook_final', call_sid: session.call_sid, evt});
  session.say({text: 'Sorry, your session has ended.'}).hangup().reply();
}

async function onEvent(session, evt) {
  session.locals.logger.info(`got eventHook: ${JSON.stringify(evt)}`);
  logEvent({event: 'event_hook', call_sid: session.call_sid, evt});
}

function onClose(session, code, reason) {
  session.locals.logger.info({code, reason}, `session ${session.call_sid} closed`);
  logEvent({event: 'session_closed', call_sid: session.call_sid, code, reason: String(reason)});
}

function onError(session, err) {
  session.locals.logger.error({err}, `session ${session.call_sid} received error`);
  logEvent({event: 'session_error', call_sid: session.call_sid, error: String(err)});
}

function attachHandlers(session) {
  session
    .on('/event', onEvent.bind(null, session))
    .on('/toolCall', onToolCall.bind(null, session))
    .on('/final', onFinal.bind(null, session))
    .on('close', onClose.bind(null, session))
    .on('error', onError.bind(null, session));
}

module.exports = {buildSetup, attachHandlers, onToolCall, handleFunctionCall, GREETING, KB_TOOL};
