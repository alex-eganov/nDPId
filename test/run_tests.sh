#!/usr/bin/env bash

set -e

LINE_SPACES=${LINE_SPACES:-48}
MYDIR="$(realpath "$(dirname ${0})")"
nDPId_test_EXEC="${2:-"$(realpath "${MYDIR}/../nDPId-test")"}"
nDPI_SOURCE_ROOT="$(realpath "${1}")"
LOCKFILE="$(realpath "${0}").lock"

touch "${LOCKFILE}"
exec 42< "${LOCKFILE}"
flock -x -n 42 || {
    printf '%s\n' "Could not aquire file lock for ${0}. Already running instance?";
    exit 1;
}

if [ $# -ne 1 -a $# -ne 2 ]; then
cat <<EOF
usage: ${0} [path-to-nDPI-source-root] [path-to-nDPId-test-exec]

	path-to-nDPId-test-exec defaults to ${nDPId_test_EXEC}
EOF
exit 1
fi

if [ ! -x "${nDPId_test_EXEC}" ]; then
cat <<EOF
Required nDPId-test executable does not exist; ${nDPId_test_EXEC}
EOF
exit 1
fi

nDPI_TEST_DIR="${nDPI_SOURCE_ROOT}/tests/pcap"

cat <<EOF
nDPId-test......: ${nDPId_test_EXEC}
nDPI source root: ${nDPI_TEST_DIR}

EOF

cd "${nDPI_TEST_DIR}"
mkdir -p /tmp/nDPId-test-stderr
set +e
RETVAL=0
for pcap_file in $(ls *.pcap*); do
    printf '%s\n' "${nDPId_test_EXEC} ${pcap_file}" \
        >"/tmp/nDPId-test-stderr/${pcap_file}.out"

    ${nDPId_test_EXEC} "${pcap_file}" \
        >"${MYDIR}/results/${pcap_file}.out.new" \
        2>>"/tmp/nDPId-test-stderr/${pcap_file}.out"

    printf "%-${LINE_SPACES}s\t" "${pcap_file}"

    if [ $? -eq 0 ]; then
        if [ ! -r "${MYDIR}/results/${pcap_file}.out" ]; then
            printf '%s\n' '[NEW]'
            RETVAL=1
        elif diff -u0 "${MYDIR}/results/${pcap_file}.out" \
                      "${MYDIR}/results/${pcap_file}.out.new" >/dev/null; then
            printf '%s\n' '[OK]'
        else
            printf '%s\n' '[DIFF]'
            diff -u0 "${MYDIR}/results/${pcap_file}.out" \
                     "${MYDIR}/results/${pcap_file}.out.new"
            mv -v "${MYDIR}/results/${pcap_file}.out.new" \
                  "${MYDIR}/results/${pcap_file}.out"
            RETVAL=1
        fi
    else
        printf '%s\n' '[FAIL]'
        printf '%s\n' '----------------------------------------'
        printf '%s\n' "-- STDERR of ${pcap_file}"
        cat "/tmp/nDPId-test-stderr/${pcap_file}.out"
        RETVAL=1
    fi

    rm -f "${MYDIR}/results/${pcap_file}.out.new"
done

cd "${MYDIR}"
for out_file in $(ls results/*.out); do
    pcap_file="${nDPI_TEST_DIR}/$(basename ${out_file%.out})"
    if [ ! -r "${pcap_file}" ]; then
        printf "%-${LINE_SPACES}s\t%s\n" "$(basename ${pcap_file})" '[MISSING]'
        RETVAL=1
    fi
done

exit ${RETVAL}
