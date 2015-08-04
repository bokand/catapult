# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import argparse
import os
import sys
import traceback

import perf_insights
from perf_insights import local_directory_corpus_driver
from perf_insights import get_trace_handles_query
from perf_insights import map_single_trace

from perf_insights import results as results_module
from perf_insights import value as value_module
from perf_insights.results import json_output_formatter
from perf_insights.results import gtest_progress_reporter

def Main(args):
  parser = argparse.ArgumentParser(
      description='Local bulk trace processing')
  parser.add_argument('trace_directory')
  parser.add_argument('--query')
  parser.add_argument('map_file')

  parser.add_argument('-o', '--output-file')
  parser.add_argument('-s', '--stop-on-error',
                      action='store_true')
  args = parser.parse_args(args)

  if not os.path.exists(args.trace_directory):
    args.error('trace_directory does not exist')
  if not os.path.exists(args.map_file):
    args.error('map does not exist')

  corpus_driver = local_directory_corpus_driver.LocalDirectoryCorpusDriver(
      os.path.abspath(os.path.expanduser(args.trace_directory)))
  if args.query is None:
    query = get_trace_handles_query.GetTraceHandlesQuery.FromString('True')
  else:
    query = get_trace_handles_query.GetTraceHandlesQuery.FromString(
        args.query)

  if args.output_file:
    ofile = open(args.output_file, 'w')
  else:
    ofile = sys.stdout

  output_formatter = json_output_formatter.JSONOutputFormatter(ofile)
  progress_reporter = gtest_progress_reporter.GTestProgressReporter(sys.stdout)
  results = results_module.Results([output_formatter], progress_reporter)

  try:
    trace_handles = corpus_driver.GetTraceHandlesMatchingQuery(query)
    _Run(results, trace_handles, args.map_file,
         stop_on_error=args.stop_on_error)
  finally:
    if ofile != sys.stdout:
      ofile.close()

  if results.had_failures:
    return 255
  return 0

def _Run(results, trace_handles, map_file,
         stop_on_error=False):

  failed_run_info_to_dump = None
  for trace_handle in trace_handles:
    run_info = trace_handle.run_info
    results.WillRun(run_info)
    map_single_trace.MapSingleTrace(
        results,
        trace_handle,
        os.path.abspath(map_file))
    results.DidRun(run_info)
    had_failure = results.DoesRunContainFailure(run_info)
    if stop_on_error and had_failure:
      failed_run_info_to_dump = run_info
      break
  results.DidFinishAllRuns()

  if failed_run_info_to_dump:
    sys.stderr.write('\n\nWhile mapping %s:\n' %
                     failed_run_info_to_dump.display_name)
    failures = [v for v in results.all_values
                if (v.run_info == failed_run_info_to_dump and
                    isinstance(v, value_module.FailureValue))]
    for failure in failures:
      print failure.GetGTestPrintString()
      sys.stderr.write('\n')