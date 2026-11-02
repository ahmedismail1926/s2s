/** Gemini Developer API route (AI Studio key); same model and GOOGLE_API_KEY as Phase 1. */
const {attachHandlers, buildSetup, GREETING} = require('./kb-shared');
const {logEvent} = require('../calllog');

const GEMINI_MODEL = process.env.GEMINI_MODEL || 'models/gemini-3.8-live';

const service = ({logger: parentLogger, makeService}) => {
  const svc = makeService({path: '/google-s2s'});

  svc.on('session:new', (session, path) => {
    const logger = parentLogger.child({call_sid: session.call_sid});
    logger.info({path}, `new incoming call: ${session.call_sid}`);
    session.locals.logger = logger;
    logEvent({event: 'session_new', call_sid: session.call_sid, model: GEMINI_MODEL});
    attachHandlers(session);

    const apiKey = process.env.GOOGLE_API_KEY;
    if (!apiKey) {
      logger.warn('GOOGLE_API_KEY env var not set, hanging up');
      session.hangup().send();
      return;
    }

    session
      .answer()
      .pause({length: 1})
      .llm({
        vendor: 'google',
        model: GEMINI_MODEL,
        auth: {apiKey},
        actionHook: '/final',
        eventHook: '/event',
        toolHook: '/toolCall',
        llmOptions: {setup: buildSetup(GEMINI_MODEL), greeting: GREETING}
      })
      .hangup()
      .send();
  });
};

module.exports = service;
