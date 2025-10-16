module.exports = function (ajv) {
  require('ajv-formats')(ajv, ['date', 'date-time', 'time']);
  return ajv;
};