import {initTripSurvey} from './trip_survey.js';

const survey = document.getElementById('trip-survey-preview');
if (survey) {
  initTripSurvey(survey, function (message) {
    document.getElementById('survey-errors').textContent = message || '';
  });
}
