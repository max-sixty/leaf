// Scenario modules declare fixed checks before execution. Missing evidence fails.
module.exports = (output, context) => {
  const check = context.config.check;
  const pass = context.providerResponse.metadata?.checks?.[check] === true;
  return {
    pass,
    score: Number(pass),
    reason: pass ? `${check}: passed` : `${check}: missing or failed`,
  };
};
