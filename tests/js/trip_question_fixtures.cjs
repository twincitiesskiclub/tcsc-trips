'use strict';

const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const ROOT = path.resolve(__dirname, '../..');
const VENV = path.join(ROOT, '.venv-linux/bin/python');
const PYTHON = process.env.PYTHON || (fs.existsSync(VENV) ? VENV : 'python3');

// The server renders dietary options. Exercise the real markup in survey tests.
const dietaryHtml = execFileSync(PYTHON, ['-c', `
from pathlib import Path
import runpy
from flask import Flask, render_template
schema = runpy.run_path('app/trips/questions.py')
app = Flask('trip_fixture', template_folder=str(Path('app/templates').resolve()))
with app.test_request_context():
    print(render_template('trips/_builtin_dietary.html', question=schema['BUILTIN_QUESTIONS']['dietary']))
`], {cwd: ROOT, encoding: 'utf8'});

module.exports = {dietaryHtml};
