#!/usr/bin/env python3

import os
import math
import sys
import time
import datetime

sys.path.append(os.path.dirname(sys.argv[0]) + '/../../dependencies')
sys.path.append(os.path.dirname(sys.argv[0]) + '/../share/nDPId')
sys.path.append(os.path.dirname(sys.argv[0]))
sys.path.append(sys.base_prefix + '/share/nDPId')
import nDPIsrvd
from nDPIsrvd import nDPIsrvdSocket, TermColor

global args
global whois_db

def set_attr_from_dict(some_object, some_dict, key_and_attr_name, default_value):
    try:
        setattr(some_object, key_and_attr_name, some_dict[key_and_attr_name])
    except KeyError:
        if default_value is not None and getattr(some_object, key_and_attr_name, None) is None:
            setattr(some_object, key_and_attr_name, default_value)

def set_attr_if_not_set(some_object, attr_name, value):
    try:
        getattr(some_object, attr_name)
    except AttributeError:
        setattr(some_object, attr_name, value)

class Stats:

    def __init__(self, nDPIsrvd_sock):
        self.statusbar_enabled = True
        self.start_time = time.time()
        self.nsock = nDPIsrvd_sock
        self.last_status_length = 0
        self.avg_xfer_json_bytes = 0.0
        self.expired_tot_l4_payload_len = 0
        self.total_flows        = 0
        self.risky_flows        = 0
        self.midstream_flows    = 0
        self.guessed_flows      = 0
        self.not_detected_flows = 0
        self.current_time  = 0.0
        self.json_lines    = 0
        self.spinner_state = 0

    def disableStatusbar(self):
        self.statusbar_enabled = False

    def updateSpinner(self):
        if self.current_time + 0.25 <= time.time():
            self.spinner_state += 1

    def __getSpinner(self):
        #spinner_states = ['-', '\\', '|', '/']
        #spinner_states = ['▉', '▊', '▋', '▌', '▍', '▎', '▏', '▎', '▍', '▌', '▋', '▊', '▉']
        spinner_states = ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙']
        #spinner_states = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█', '▇', '▆', '▅', '▄', '▃', '▁']
        #spinner_states = ['▖', '▘', '▝', '▗']
        #spinner_states = ['┤', '┘', '┴', '└', '├', '┌', '┬', '┐']
        return spinner_states[self.spinner_state % len(spinner_states)]

    def __getDataFromJson(self, json_dict, current_flow):
        if current_flow is None:
            return

        set_attr_from_dict(current_flow, json_dict, 'flow_src_tot_l4_payload_len', 0)
        set_attr_from_dict(current_flow, json_dict, 'flow_dst_tot_l4_payload_len', 0)
        if 'ndpi' in json_dict:
            set_attr_from_dict(current_flow, json_dict['ndpi'], 'flow_risk', {})
        else:
            set_attr_from_dict(current_flow, {}, 'flow_risk', {})
        set_attr_from_dict(current_flow, json_dict, 'midstream', 0)
        set_attr_from_dict(current_flow, json_dict, 'flow_event_name', '')
        set_attr_if_not_set(current_flow, 'guessed', 0)
        set_attr_if_not_set(current_flow, 'not_detected', 0)

        if current_flow.flow_event_name == 'detected' or \
           current_flow.flow_event_name == 'detection-update':
            current_flow.guessed = 0
        elif current_flow.flow_event_name == 'guessed':
            current_flow.guessed = 1
        elif current_flow.flow_event_name == 'not-detected':
            current_flow.not_detected = 1

    def update(self, json_dict, current_flow):
        self.updateSpinner()
        self.json_lines += 1
        self.current_time = time.time()
        self.avg_xfer_json_bytes = self.nsock.received_bytes / (self.current_time - self.start_time)
        self.__getDataFromJson(json_dict, current_flow)

    def updateOnCleanup(self, current_flow):
        self.total_flows += 1
        self.expired_tot_l4_payload_len += current_flow.flow_src_tot_l4_payload_len + current_flow.flow_dst_tot_l4_payload_len
        self.risky_flows += 1 if len(current_flow.flow_risk) > 0 else 0
        self.midstream_flows += 1 if current_flow.midstream != 0 else 0
        self.guessed_flows += 1 if current_flow.guessed != 0 else 0
        self.not_detected_flows += 1 if current_flow.not_detected != 0 else 0

    def __getStatsFromFlowMgr(self):
        alias_count = 0
        source_count = 0
        flow_count = 0
        flow_tot_l4_payload_len = 0.0
        risky = 0
        midstream = 0
        guessed = 0
        not_detected = 0

        instances = self.nsock.flow_mgr.instances
        for alias in instances:
            alias_count += 1
            for source in instances[alias]:
                source_count += 1
                for flow_id in instances[alias][source].flows:
                    flow_count += 1
                    current_flow = instances[alias][source].flows[flow_id]

                    try:
                        flow_src_tot_l4_payload_len = current_flow.flow_src_tot_l4_payload_len
                        flow_dst_tot_l4_payload_len = current_flow.flow_dst_tot_l4_payload_len
                        flow_risk = current_flow.flow_risk
                        midstream = current_flow.midstream
                        guessed = current_flow.guessed
                        not_detected = current_flow.not_detected
                    except AttributeError:
                        flow_src_tot_l4_payload_len = 0
                        flow_dst_tot_l4_payload_len = 0
                        flow_risk = []
                        midstream = 0
                        guessed = 0
                        not_detected = 0

                    flow_tot_l4_payload_len += flow_src_tot_l4_payload_len + flow_dst_tot_l4_payload_len
                    risky += 1 if len(flow_risk) > 0 else 0
                    midstream += 1 if midstream != 0 else 0
                    guessed += 1 if guessed != 0 else 0
                    not_detected = 1 if not_detected != 0 else 0

        return alias_count, source_count, flow_count, \
               flow_tot_l4_payload_len, \
               risky, midstream, guessed, not_detected

    @staticmethod
    def prettifyBytes(bytes_received, is_byte_unit = True):
        if not is_byte_unit:
            size_names = ['', 'K', 'M', 'G', 'T']
            divisor = 1000
        else:
            size_names = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
            divisor = 1024

        if bytes_received == 0:
            i = 0
        else:
            i = min(int(math.floor(math.log(bytes_received, divisor))), len(size_names) - 1)
        p = math.pow(divisor, i)
        s = round(bytes_received / p, 2)

        if not is_byte_unit:
            return '{:.0f}{}'.format(s, ' ' + size_names[i] if len(size_names[i]) > 0 else size_names[i])
        else:
            return '{:.2f} {}'.format(s, size_names[i])

    def resetStatus(self):
        if self.statusbar_enabled is False:
            return

        sys.stdout.write('\r' + str(' ' * self.last_status_length) + '\r')
        sys.stdout.flush()

    def printStatus(self):
        if self.statusbar_enabled is False:
            return

        alias_count, source_count, flow_count, \
        tot_l4_payload_len, \
        risky, midstream, guessed, not_detected = self.__getStatsFromFlowMgr()

        out_str = '\r[n|tot|avg JSONs: {}|{}|{}/s] [tot l4: {}] ' \
            '[lss|srcs: {}|{}] ' \
            '[flws|rsky|mdstrm|!dtctd|gssd: {}|{}|{}|{}|{} / {}|{}|{}|{}|{}] [{}]' \
            ''.format(self.json_lines,
                      Stats.prettifyBytes(self.nsock.received_bytes),
                      Stats.prettifyBytes(self.avg_xfer_json_bytes),
                      Stats.prettifyBytes(tot_l4_payload_len + self.expired_tot_l4_payload_len),
                      alias_count, source_count,
                      flow_count, risky, midstream, not_detected, guessed,
                      flow_count + self.total_flows,
                      risky + self.risky_flows,
                      midstream + self.midstream_flows,
                      not_detected + self.not_detected_flows,
                      guessed + self.guessed_flows,
                      self.__getSpinner())
        self.last_status_length = len(out_str) - 1 # '\r'

        sys.stdout.write(out_str)
        sys.stdout.flush()

def prettifyEvent(color_list, whitespaces, text):
    term_attrs = str()
    for color in color_list:
        term_attrs += str(color)
    fmt = '{}{:>' + str(whitespaces) + '}{}'
    return fmt.format(term_attrs, text, TermColor.END)

def prettifyTimediff(epoch_ts1, epoch_ts2):
    dt1 = datetime.datetime.fromtimestamp(epoch_ts1)
    dt2 = datetime.datetime.fromtimestamp(epoch_ts2)
    seconds_diff = (dt2 - dt1).total_seconds()
    return '{:.>4}m{:.>3}s'.format(int(seconds_diff / 60), int(seconds_diff) % 60)

def checkEventFilter(json_dict):
    flow_events = {'new': args.new, 'end': args.end, 'idle': args.idle,
                   'guessed': args.guessed, 'detected': args.detected,
                   'detection-update': args.detection_update,
                   'not-detected': args.not_detected,
                   'update': args.update, 'analyse': args.analyse}

    if flow_events[json_dict['flow_event_name']] is True:
        return True

    if 'ndpi' in json_dict and 'flow_risk' in json_dict['ndpi']:
        if args.risky is True:
            return True

    if json_dict['midstream'] != 0:
        if args.midstream is True:
            return True

    flow_event_filter_disabled = True
    for flow_event in list(flow_events.values()) + [args.risky, args.midstream]:
        if flow_event is True:
            flow_event_filter_disabled = False
            break
    if flow_event_filter_disabled is True:
        return True

    return False

def whois(ip_str):
    if ip_str not in whois_db:
        try:
            whois_json = ipwhois.ipwhois.IPWhois(ip_str).lookup_whois()
            whois_db[ip_str] = whois_json['asn_description']
        except (ipwhois.exceptions.IPDefinedError, dns.resolver.NoResolverConfiguration):
            return None
    return whois_db[ip_str]

def onFlowCleanup(instance, current_flow, global_user_data):
    stats = global_user_data
    stats.updateOnCleanup(current_flow)

    return True

def limitFloatValue(value, fmt, limit):
    if float(value) < float(limit) and float(value) > 0.0:
        return '<' + str(fmt).format(limit)
    else:
        return ' ' + str(fmt).format(value)

def onJsonLineRecvd(json_dict, instance, current_flow, global_user_data):
    stats = global_user_data
    stats.update(json_dict, current_flow)

    if 'packet_event_id' in json_dict:
        return True

    stats.resetStatus()

    instance_and_source = ''
    if args.hide_instance_info is False:
        instance_and_source += '[{}][{}][{:.>2}] '.format(
                        TermColor.setColorByString(instance.alias),
                        TermColor.setColorByString(instance.source),
                        json_dict['thread_id'] if 'thread_id' in json_dict else '')
    else:
        instance_and_source += ' '

    basic_daemon_event_prefix = ''
    timestamp = ''
    if args.print_timestamp is True:
        if 'thread_ts_usec' in json_dict:
            timestamp += '[{}]'.format(time.strftime('%H:%M:%S',
                                       time.localtime(nDPIsrvd.toSeconds(json_dict['thread_ts_usec']))))
        elif 'global_ts_usec' in json_dict:
            timestamp += '[{}]'.format(time.strftime('%H:%M:%S',
                                       time.localtime(nDPIsrvd.toSeconds(json_dict['global_ts_usec']))))

    first_seen = ''
    if args.print_first_seen is True:
        basic_daemon_event_prefix += ' ' * 11
        if 'flow_first_seen' in json_dict:
            first_seen = '[' + prettifyTimediff(nDPIsrvd.toSeconds(json_dict['flow_first_seen']),
                                                nDPIsrvd.toSeconds(json_dict['thread_ts_usec'])) + ']'

    last_seen = ''
    if args.print_last_seen is True:
        basic_daemon_event_prefix +=  ' ' * 11
        if current_flow is not None:
            flow_last_seen = nDPIsrvd.FlowManager.getLastPacketTime(instance, current_flow.flow_id, json_dict)
            last_seen = '[' + prettifyTimediff(nDPIsrvd.toSeconds(flow_last_seen),
                                               nDPIsrvd.toSeconds(json_dict['thread_ts_usec'])) + ']'

    if 'daemon_event_id' in json_dict:
        if json_dict['daemon_event_name'] == 'status':
            color = [TermColor.WARNING]
            daemon_msg = list()
            daemon_msg += ['[Processed: {} pkts][ZLib][compressions: {}|diff: {} / {}]'.format(
                             json_dict['packets-processed'],
                             json_dict['total-compressions'], json_dict['current-compression-diff'], json_dict['total-compression-diff'])]
            daemon_msg += ['[Flows][active: {} / {}|skipped: {}|!detected: {}|guessed: {}|' \
                                   'detection-updates: {}|updates: {}]'.format(
                             json_dict['current-active-flows'], json_dict['total-active-flows'],
                             json_dict['total-skipped-flows'],
                             json_dict['total-not-detected-flows'], json_dict['total-guessed-flows'],
                             json_dict['total-detection-updates'], json_dict['total-updates'])]
        else:
            color = [TermColor.WARNING, TermColor.BLINK]
            daemon_msg = list()
            daemon_msg += [json_dict['daemon_event_name']]
        for dm in daemon_msg:
            print('{}{}{} {}: {}'.format(timestamp, basic_daemon_event_prefix, instance_and_source,
                                         prettifyEvent(color, 15, 'DAEMON-EVENT'), dm))
        stats.printStatus()
        return True
    if 'error_event_id' in json_dict:
        print('{}{}{} {}: {} [{}/{}]'.format(timestamp, basic_daemon_event_prefix, instance_and_source,
                                 prettifyEvent([TermColor.FAIL, TermColor.BLINK], 15, 'ERROR-EVENT'),
                                 json_dict['error_event_name'], json_dict['threshold_n'], json_dict['threshold_n_max']))
        stats.printStatus()
        return True
    elif 'flow_event_id' not in json_dict:
        stats.printStatus()
        return True

    if checkEventFilter(json_dict) is False:
        stats.printStatus()
        return True

    ndpi_proto_categ_breed = ''
    next_lines = []

    if 'ndpi' in json_dict:
        ndpi_proto_categ_breed += ' '

        if 'proto' in json_dict['ndpi']:
            if args.ignore_protocol is not None:
                for proto in args.ignore_protocol:
                    if json_dict['ndpi']['proto'].lower().startswith(proto.lower()) is True:
                        stats.printStatus()
                        return True
            ndpi_proto_categ_breed += '[' + str(json_dict['ndpi']['proto']) + ']'

        if 'proto_by_ip' in json_dict['ndpi']:
            if args.ignore_ip_protocol is not None:
                for proto in args.ignore_ip_protocol:
                    if json_dict['ndpi']['proto_by_ip'].lower().startswith(proto.lower()) is True:
                        stats.printStatus()
                        return True
            ndpi_proto_categ_breed += '[' + str(json_dict['ndpi']['proto_by_ip']) + ']'

        if 'category' in json_dict['ndpi']:
            if args.ignore_category is not None:
                for cat in args.ignore_category:
                    if json_dict['ndpi']['category'].lower().startswith(cat.lower()) is True:
                        stats.printStatus()
                        return True
            ndpi_proto_categ_breed += '[' + str(json_dict['ndpi']['category']) + ']'

        if 'breed' in json_dict['ndpi']:
            if args.ignore_breed is not None:
                for breed in args.ignore_breed:
                    if json_dict['ndpi']['breed'].lower().startswith(breed.lower()) is True:
                        stats.printStatus()
                        return True
            ndpi_proto_categ_breed += '[' + str(json_dict['ndpi']['breed']) + ']'

        if 'flow_risk' in json_dict['ndpi'] and args.hide_risk_info == False:
            severity = 0
            cnt = 0

            next_lines += ['']
            for key in json_dict['ndpi']['flow_risk']:
                next_lines[0] += str(json_dict['ndpi']['flow_risk'][key]['risk']) + ', '
                if json_dict['ndpi']['flow_risk'][key]['severity'] == 'Low':
                    severity = max(severity, 1)
                elif json_dict['ndpi']['flow_risk'][key]['severity'] == 'Medium':
                    severity = max(severity, 2)
                elif json_dict['ndpi']['flow_risk'][key]['severity'] == 'High':
                    severity = max(severity, 3)
                elif json_dict['ndpi']['flow_risk'][key]['severity'] == 'Severe':
                    severity = max(severity, 4)
                cnt += 1

            if severity == 1:
                color = TermColor.WARNING + TermColor.BOLD
            elif severity == 2:
                color = TermColor.WARNING + TermColor.BOLD + TermColor.BLINK
            elif severity == 3:
                color = TermColor.FAIL + TermColor.BOLD
            elif severity == 4:
                color = TermColor.FAIL + TermColor.BOLD + TermColor.BLINK
            else:
                color = ''

            if severity >= args.min_risk_severity:
                next_lines[0] = '{}{}{}: {}'.format(color, 'RISK', TermColor.END, next_lines[0][:-2])
            else:
                del next_lines[0]

    line_suffix = ''
    flow_event_name = ''
    flow_active_color = '' if json_dict['flow_state'] == 'finished' else TermColor.BOLD
    if json_dict['flow_event_name'] == 'guessed':
        flow_event_name += '{}{:>16}{}'.format(TermColor.HINT + flow_active_color,
                                               json_dict['flow_event_name'], TermColor.END)
    elif json_dict['flow_event_name'] == 'not-detected':
        flow_event_name += '{}{:>16}{}'.format(TermColor.WARNING + TermColor.BOLD + TermColor.BLINK,
                                               json_dict['flow_event_name'], TermColor.END)
    elif json_dict['flow_event_name'] == 'analyse':
        flow_event_name += '{}{:>16}{}'.format(TermColor.WARNING,
                                               json_dict['flow_event_name'], TermColor.END)
        if args.print_analyse_results is True:
            next_lines =  ['               {:>10}|{:>10}|{:>10}|{:>10}|{:>17}|{:>9}'.format(
                           'min', 'max', 'avg', 'stddev', 'variance', 'entropy')]
            next_lines += ['[IAT.........: {}|{}|{}|{}|{}|{}]'.format(
                               limitFloatValue(nDPIsrvd.toSeconds(json_dict['data_analysis']['iat']['min']),
                                               '{:>9.3f}', 0.001),
                               limitFloatValue(nDPIsrvd.toSeconds(json_dict['data_analysis']['iat']['max']),
                                               '{:>9.3f}', 0.001),
                               limitFloatValue(nDPIsrvd.toSeconds(json_dict['data_analysis']['iat']['avg']),
                                               '{:>9.3f}', 0.001),
                               limitFloatValue(nDPIsrvd.toSeconds(json_dict['data_analysis']['iat']['stddev']),
                                               '{:>9.3f}', 0.001),
                               limitFloatValue(nDPIsrvd.toSeconds(json_dict['data_analysis']['iat']['var']),
                                               '{:>16.3f}', 0.001),
                               limitFloatValue(json_dict['data_analysis']['iat']['ent'],
                                               '{:>8.3f}', 0.001)
                          )]
            next_lines += ['']
            next_lines[-1] += '[PKTLEN......: {}|{}|{}|{}|{}|{}]'.format(
                                  limitFloatValue(json_dict['data_analysis']['pktlen']['min'], '{:>9.3f}', 0.001),
                                  limitFloatValue(json_dict['data_analysis']['pktlen']['max'], '{:>9.3f}', 0.001),
                                  limitFloatValue(json_dict['data_analysis']['pktlen']['avg'], '{:>9.3f}', 0.001),
                                  limitFloatValue(json_dict['data_analysis']['pktlen']['stddev'],
                                                  '{:>9.3f}', 0.001),
                                  limitFloatValue(json_dict['data_analysis']['pktlen']['var'], '{:>16.3f}', 0.001),
                                  limitFloatValue(json_dict['data_analysis']['pktlen']['ent'], '{:>8.3f}', 0.001)
                              )
            next_lines += ['']
            next_lines[-1] += '[BINS(c->s)..: {}]'.format(','.join([str(n) for n in json_dict['data_analysis']['bins']['c_to_s']]))
            next_lines += ['']
            next_lines[-1] += '[BINS(s->c)..: {}]'.format(','.join([str(n) for n in json_dict['data_analysis']['bins']['s_to_c']]))
            next_lines += ['']
            next_lines[-1] += '[DIRECTIONS..: {}]'.format(','.join([str(n) for n in json_dict['data_analysis']['directions']]))
            next_lines += ['']
            iats = ''
            for n in json_dict['data_analysis']['iat']['data']:
                iats += '{:.1f},'.format(n / 1000.0)
            iats = iats[:-1]
            next_lines[-1] += '[IATS(ms)....: {}]'.format(iats)
            next_lines += ['']
            next_lines[-1] += '[PKTLENS.....: {}]'.format(','.join([str(n) for n in json_dict['data_analysis']['pktlen']['data']]))
            next_lines += ['']
            ents = ''
            for n in json_dict['data_analysis']['entropies']:
                ents += '{:.1f},'.format(n)
            ents = ents[:-1]
            next_lines[-1] += '[ENTROPIES...: {}]'.format(ents)
    else:
        if json_dict['flow_event_name'] == 'new':
            line_suffix = ''
            if json_dict['midstream'] != 0:
                line_suffix += ' [{}]'.format(TermColor.WARNING + TermColor.BLINK + 'MIDSTREAM' + TermColor.END)
            if args.ipwhois is True:
                src_whois = whois(json_dict['src_ip'].lower())
                dst_whois = whois(json_dict['dst_ip'].lower())
                line_suffix += ' ['
                if src_whois is not None:
                    line_suffix += '{}'.format(src_whois)
                if dst_whois is not None:
                    if src_whois is not None:
                        line_suffix += ' -> '
                    line_suffix += '{}'.format(dst_whois)
                if src_whois is None and dst_whois is None:
                    line_suffix += TermColor.WARNING + 'WHOIS empty' + TermColor.END
                line_suffix += ']'
        flow_event_name += '{}{:>16}{}'.format(flow_active_color, json_dict['flow_event_name'], TermColor.END)

    if 'ndpi' in json_dict and 'hostname' in json_dict['ndpi']:
        if args.ignore_hostname is not None:
            for hostname in args.ignore_hostname:
                if json_dict['ndpi']['hostname'].lower().endswith(hostname.lower()) is True:
                    stats.printStatus()
                    return True
        if args.print_hostname is True:
            line_suffix += '[{}]'.format(json_dict['ndpi']['hostname'])

    if args.skip_empty is True:
        if json_dict['flow_src_tot_l4_payload_len'] == 0 or json_dict['flow_dst_tot_l4_payload_len'] == 0:
            stats.printStatus()
            return True

    if args.print_bytes is True:
        src_color = ''
        dst_color = ''
        tot_color = ''
        if json_dict['flow_src_tot_l4_payload_len'] >= 1 * 1024 * 1024:
            tot_color = src_color = TermColor.HINT
            if json_dict['flow_src_tot_l4_payload_len'] >= 1 * 1024 * 1024 * 1024:
                src_color += TermColor.BOLD + TermColor.BLINK
        if json_dict['flow_dst_tot_l4_payload_len'] >= 1 * 1024 * 1024:
            tot_color = dst_color = TermColor.HINT
            if json_dict['flow_dst_tot_l4_payload_len'] >= 1 * 1024 * 1024 * 1024:
                dst_color += TermColor.BOLD + TermColor.BLINK
        line_suffix += '[' + src_color + Stats.prettifyBytes(json_dict['flow_src_tot_l4_payload_len']) + TermColor.END + ']' \
                       '[' + dst_color + Stats.prettifyBytes(json_dict['flow_dst_tot_l4_payload_len']) + TermColor.END +']' \
                       '[' + tot_color + Stats.prettifyBytes(json_dict['flow_src_tot_l4_payload_len'] + \
                                                             json_dict['flow_dst_tot_l4_payload_len']) + TermColor.END + ']'

    if args.print_packets is True:
        line_suffix += '[' + Stats.prettifyBytes(json_dict['flow_src_packets_processed'], False) + ']' \
                       '[' + Stats.prettifyBytes(json_dict['flow_dst_packets_processed'], False) + ']'

    if json_dict['l3_proto'] == 'ip4':
        print('{}{}{}{}{}: [{:.>6}]{} [{}][{:.>5}] [{:.>15}]{} -> [{:.>15}]{}{}{}' \
              ''.format(timestamp, first_seen, last_seen, instance_and_source, flow_event_name, 
              json_dict['flow_id'],
              '[{:.>4}]'.format(json_dict['vlan_id']) if 'vlan_id' in json_dict else '',
              json_dict['l3_proto'], json_dict['l4_proto'],
              json_dict['src_ip'].lower(),
              '[{:.>5}]'.format(json_dict['src_port']) if 'src_port' in json_dict else '',
              json_dict['dst_ip'].lower(),
              '[{:.>5}]'.format(json_dict['dst_port']) if 'dst_port' in json_dict else '',
              ndpi_proto_categ_breed, line_suffix))
    elif json_dict['l3_proto'] == 'ip6':
        print('{}{}{}{}{}: [{:.>6}] [{}][{:.>5}] [{:.>39}]{} -> [{:.>39}]{}{}{}' \
                ''.format(timestamp, first_seen, last_seen, instance_and_source, flow_event_name,
              json_dict['flow_id'], json_dict['l3_proto'], json_dict['l4_proto'],
              json_dict['src_ip'].lower(),
              '[{:.>5}]'.format(json_dict['src_port']) if 'src_port' in json_dict else '',
              json_dict['dst_ip'].lower(),
              '[{:.>5}]'.format(json_dict['dst_port']) if 'dst_port' in json_dict else '',
              ndpi_proto_categ_breed, line_suffix))
    else:
        raise RuntimeError('unsupported l3 protocol: {}'.format(json_dict['l3_proto']))

    for line in next_lines:
        print('{}{}{}{}{:>18}{}'.format(timestamp, first_seen, last_seen,
                                        instance_and_source, '', line))

    stats.printStatus()

    return True

if __name__ == '__main__':
    argparser = nDPIsrvd.defaultArgumentParser('Prettify and print events using the nDPIsrvd Python interface.', True)
    argparser.add_argument('--no-color', action='store_true', default=False,
                           help='Disable all terminal colors.')
    argparser.add_argument('--no-blink', action='store_true', default=False,
                           help='Disable all blink effects.')
    argparser.add_argument('--no-statusbar', action='store_true', default=False,
                           help='Disable informational status bar.')
    argparser.add_argument('--hide-instance-info', action='store_true', default=False,
                           help='Hide instance Alias/Source prefixed every line.')
    argparser.add_argument('--hide-risk-info', action='store_true', default=False,
                           help='Skip printing risks.')
    argparser.add_argument('--print-timestamp', action='store_true', default=False,
                           help='Print received event timestamps.')
    argparser.add_argument('--print-first-seen', action='store_true', default=False,
                           help='Print first seen flow time diff.')
    argparser.add_argument('--print-last-seen', action='store_true', default=False,
                           help='Print last seen flow time diff.')
    argparser.add_argument('--print-bytes', action='store_true', default=False,
                           help='Print received/transmitted source/dest bytes for every flow.')
    argparser.add_argument('--print-packets', action='store_true', default=False,
                           help='Print received/transmitted source/dest packets for every flow.')
    argparser.add_argument('--skip-empty', action='store_true', default=False,
                           help='Do not print flows that did not carry any layer7 payload.')
    argparser.add_argument('--guessed',    action='store_true', default=False, help='Print only guessed flow events.')
    argparser.add_argument('--not-detected', action='store_true', default=False, help='Print only undetected flow events.')
    argparser.add_argument('--detected',   action='store_true', default=False, help='Print only detected flow events.')
    argparser.add_argument('--detection-update', action='store_true', default=False, help='Print only detection-update flow events.')
    argparser.add_argument('--risky',      action='store_true', default=False, help='Print only risky flow events.')
    argparser.add_argument('--midstream',  action='store_true', default=False, help='Print only midstream flow events.')
    argparser.add_argument('--new',        action='store_true', default=False, help='Print only new flow events.')
    argparser.add_argument('--end',        action='store_true', default=False, help='Print only end flow events.')
    argparser.add_argument('--idle',       action='store_true', default=False, help='Print only idle flow events.')
    argparser.add_argument('--update',     action='store_true', default=False, help='Print only update flow events.')
    argparser.add_argument('--analyse',    action='store_true', default=False, help='Print only analyse flow events.')
    argparser.add_argument('--detection',  action='store_true', default=False, help='Print only detected/guessed/not-detected flow events.')
    argparser.add_argument('--ipwhois',    action='store_true', default=False, help='Use Python-IPWhois to print additional location information.')
    argparser.add_argument('--print-hostname', action='store_true', default=False, help='Print detected hostnames if available.')
    argparser.add_argument('--print-analyse-results', action='store_true', default=False,
                           help='Print detailed results of analyse events.')
    argparser.add_argument('--ignore-protocol', action='append', help='Ignore printing lines with a certain protocol.')
    argparser.add_argument('--ignore-ip-protocol', action='append', help='Ignore printing lines with a certain IP protocol.')
    argparser.add_argument('--ignore-category', action='append', help='Ignore printing lines with a certain category.')
    argparser.add_argument('--ignore-breed', action='append', help='Ignore printing lines with a certain breed.')
    argparser.add_argument('--ignore-hostname', action='append', help='Ignore printing lines with a certain hostname.')
    argparser.add_argument('--min-risk-severity', action='store', type=int, default=0, help='Print only risks with a risk severity greater or equal to the given argument')
    args = argparser.parse_args()

    if args.no_color is True:
        TermColor.disableColor()

    if args.no_blink is True:
        TermColor.disableBlink()

    if args.ipwhois is True:
        import dns, ipwhois
        whois_db = dict()

    if args.detection is True:
        args.detected = True
        args.guessed = True
        args.not_detected = True

    address = nDPIsrvd.validateAddress(args)

    sys.stderr.write('Recv buffer size: {}\n'.format(nDPIsrvd.NETWORK_BUFFER_MAX_SIZE))
    sys.stderr.write('Connecting to {} ..\n'.format(address[0]+':'+str(address[1]) if type(address) is tuple else address))

    nsock = nDPIsrvdSocket()
    nDPIsrvd.prepareJsonFilter(args, nsock)
    nsock.connect(address)
    nsock.timeout(1.0)
    stats = Stats(nsock)

    if args.no_statusbar is True:
        stats.disableStatusbar()

    while True:
        try:
            nsock.loop(onJsonLineRecvd, onFlowCleanup, stats)
        except nDPIsrvd.SocketConnectionBroken as err:
            sys.stderr.write('\n{}\n'.format(err))
            break
        except KeyboardInterrupt:
            print('\n\nKeyboard Interrupt: cleaned up {} flows.'.format(len(nsock.shutdown())))
            break
        except nDPIsrvd.SocketTimeout:
            stats.updateSpinner()
            stats.resetStatus()
            stats.printStatus()
