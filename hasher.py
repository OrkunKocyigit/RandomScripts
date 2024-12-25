import time

import siphash24
import numpy as np
import pyopencl as cl
import argparse
import os
import csv

# Define OpenCL kernel for SHA-1 hashing
kernel_code = """
__kernel void sha1_kernel(__global const uchar *input, __global uchar *output, __global int *lengths) {
    // SHA-1 constants
    uint h0 = 0x67452301;
    uint h1 = 0xEFCDAB89;
    uint h2 = 0x98BADCFE;
    uint h3 = 0x10325476;
    uint h4 = 0xC3D2E1F0;

    uint k[] = {0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xCA62C1D6};

    int idx = get_global_id(0);
    int length = lengths[idx];

    // Process the message in 512-bit (64-byte) chunks
    uchar chunk[64];
    uint w[80];

    for (int chunk_idx = 0; chunk_idx <= length / 64; chunk_idx++) {
        for (int i = 0; i < 64; i++) {
            int pos = chunk_idx * 64 + i;
            if (pos < length) {
                chunk[i] = input[pos];
            } else if (pos == length) {
                chunk[i] = 0x80;
            } else {
                chunk[i] = 0;
            }
        }

        // Padding length in last chunk
        if (chunk_idx == length / 64) {
            uint bit_len = length * 8;
            for (int i = 0; i < 8; i++) {
                chunk[63 - i] = bit_len & 0xFF;
                bit_len >>= 8;
            }
        }

        // Break chunk into 16 words w[0..15] of 32 bits
        for (int i = 0; i < 16; i++) {
            w[i] = chunk[4 * i] << 24 |
                   chunk[4 * i + 1] << 16 |
                   chunk[4 * i + 2] << 8 |
                   chunk[4 * i + 3];
        }

        // Extend the first 16 words into the remaining 64 words w[16..79]
        for (int i = 16; i < 80; i++) {
            uint temp = w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16];
            w[i] = (temp << 1) | (temp >> 31);
        }

        // Initialize hash value for this chunk
        uint a = h0;
        uint b = h1;
        uint c = h2;
        uint d = h3;
        uint e = h4;

        // Main loop
        for (int i = 0; i < 80; i++) {
            uint f, k_temp;
            if (i < 20) {
                f = (b & c) | (~b & d);
                k_temp = k[0];
            } else if (i < 40) {
                f = b ^ c ^ d;
                k_temp = k[1];
            } else if (i < 60) {
                f = (b & c) | (b & d) | (c & d);
                k_temp = k[2];
            } else {
                f = b ^ c ^ d;
                k_temp = k[3];
            }
            uint temp = ((a << 5) | (a >> 27)) + f + e + k_temp + w[i];
            e = d;
            d = c;
            c = (b << 30) | (b >> 2);
            b = a;
            a = temp;
        }

        // Add this chunk's hash to result so far
        h0 += a;
        h1 += b;
        h2 += c;
        h3 += d;
        h4 += e;
    }

    // Output the final hash
    uint hash[] = {h0, h1, h2, h3, h4};
    for (int i = 0; i < 5; i++) {
        output[idx * 20 + i * 4]     = hash[i] >> 24;
        output[idx * 20 + i * 4 + 1] = hash[i] >> 16;
        output[idx * 20 + i * 4 + 2] = hash[i] >> 8;
        output[idx * 20 + i * 4 + 3] = hash[i];
    }
}
"""

def list_opencl_devices():
    platforms = cl.get_platforms()
    for platform in platforms:
        devices = platform.get_devices()
        for device_id, device in enumerate(devices):
            print(f"Device ID: {device_id}, Name: {device.name}, Type: {cl.device_type.to_string(device.type)}")


def select_best_device(devices):
    sorted_devices = sorted(devices, key=lambda d: (
    -d.global_mem_size, d.vendor.lower().startswith('nvidia'), d.vendor.lower().startswith('amd'),
    d.vendor.lower().startswith('intel')))
    return sorted_devices[0]


def generate_unique_filename(base_name, directory):
    for i in range(1000):
        filename = f"{base_name}_{i:03d}.txt"
        full_path = os.path.join(directory, filename)
        if not os.path.exists(full_path):
            return full_path
    raise FileExistsError("All possible output filenames (up to 999) are taken.")


def scan_directory(path, recursive=False):
    file_list = []
    if recursive:
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                if os.access(file_path, os.R_OK):
                    file_list.append(file_path)
    else:
        for entry in os.scandir(path):
            if entry.is_file() and os.access(entry.path, os.R_OK):
                file_list.append(entry.path)
    return file_list


def perform_hashing(context, queue, program, file_paths):
    hashes = []
    sha1_size = 20  # SHA-1 produces a 20-byte hash

    for file_path in file_paths:
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # Allocate buffers
        mf = cl.mem_flags
        input_buffer = cl.Buffer(context, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=file_data)
        output_buffer = cl.Buffer(context, mf.WRITE_ONLY, sha1_size)
        lengths = np.array([len(file_data)], dtype=np.int32)
        lengths_buffer = cl.Buffer(context, mf.READ_ONLY | mf.COPY_HOST_PTR, hostbuf=lengths)

        # Execute the kernel
        sha1_kernel = program.sha1_kernel
        sha1_kernel.set_args(input_buffer, output_buffer, lengths_buffer)
        cl.enqueue_nd_range_kernel(queue, sha1_kernel, (1,), None)

        # Read the results
        output_data = np.empty(sha1_size, dtype=np.uint8)
        cl.enqueue_copy(queue, output_data, output_buffer).wait()

        # Convert to hex and add to results
        hash_hex = ''.join(format(byte, '02x') for byte in output_data)
        hashes.append((file_path, hash_hex))

    return hashes

def main():
    parser = argparse.ArgumentParser(description="Batch Hashing of Files")
    parser.add_argument("path", type=str, help="Path to the directory containing files", nargs='?')
    parser.add_argument("-l", "--list", action="store_true", help="List available OpenCL devices")
    parser.add_argument("-d", "--device", type=int, help="Select a specific GPU device by ID", default=None)
    parser.add_argument("-o", "--output", type=str, help="Path to the output file", default=None)
    parser.add_argument("-r", "--recursive", action="store_true", help="Scan directories recursively")

    args = parser.parse_args()

    if args.list:
        list_opencl_devices()
        return

    if not args.path:
        print("Error: Path to the directory is required.")
        return

    # Check if the path is a directory and has read permission
    if not os.path.isdir(args.path):
        print(f"Error: {args.path} is not a directory.")
        return

    if not os.access(args.path, os.R_OK):
        print(f"Error: No read permission for directory {args.path}.")
        return

    # Determine output file path
    if args.output:
        output_path = args.output
        if not os.path.isabs(output_path):
            output_path = os.path.join(os.getcwd(), output_path)
        if os.path.exists(output_path):
            print(f"Error: The file {output_path} already exists.")
            return
    else:
        output_dir = os.getcwd()
        base_name = "output"
        output_path = os.path.join(output_dir, f"{base_name}.csv")
        if os.path.exists(output_path):
            output_path = generate_unique_filename(base_name, output_dir)

    output_dir = os.path.dirname(output_path)
    if not os.access(output_dir, os.W_OK):
        print(f"Error: No write permission for directory {output_dir}.")
        return

    # Initialize OpenCL
    platforms = cl.get_platforms()
    if not platforms:
        print("No OpenCL platforms found.")
        return
    devices = platforms[0].get_devices()
    if not devices:
        print("No OpenCL devices found.")
        return

    if args.device is not None:
        if args.device < 0 or args.device >= len(devices):
            print(f"Error: Device ID {args.device} is out of range.")
            return
        selected_device = devices[args.device]
    else:
        selected_device = select_best_device(devices)

    context = cl.Context([selected_device])
    queue = cl.CommandQueue(context)

    # Build OpenCL program
    program = cl.Program(context, kernel_code).build()

    # Record start time
    start_time = time.time()

    # Scan directory for files
    files_to_process = scan_directory(args.path, args.recursive)
    print(f"Found {len(files_to_process)} files to process.")

    # Perform hashing
    try:
        hashes = perform_hashing(context, queue, program, files_to_process)

        # Write results to output file
        with open(output_path, "w", newline='') as csvfile:
            csvwriter = csv.writer(csvfile, delimiter='|')
            csvwriter.writerow(['FILE_PATH', 'FILE_NAME', 'FILE_EXTENSION', 'HASH'])
            for file, hash in hashes:
                file_name = os.path.basename(file)
                file_extension = os.path.splitext(file_name)[1]
                csvwriter.writerow([file, file_name, file_extension, hash])

        print(f"Hashes successfully written to {output_path}")

        # Record end time and print duration
        end_time = time.time()
        print(f"Total time taken: {end_time - start_time:.2f} seconds")

    except Exception as e:
        print(f"Error during hashing: {e}")

if __name__ == "__main__":
    main()
