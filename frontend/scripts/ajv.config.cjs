// frontend/scripts/ajv.config.cjs
module.exports = function (ajv) {
  // slå på standardformater (date, date-time, time, email, uri, m.m.)
  require('ajv-formats')(ajv, ['date', 'date-time', 'time']);
  return ajv;
};