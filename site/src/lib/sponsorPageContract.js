// @ts-check

// Shared by Astro's production content validation and Keystatic's editor validation.
export const SPONSOR_CONTACT_EMAIL_PATTERN =
  /^(?!.*\.\.)[a-z0-9_'+-](?:[a-z0-9_'+.-]*[a-z0-9_'+-])?@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i;
