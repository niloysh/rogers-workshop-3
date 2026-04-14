HTB queues give us soft slicing — h1's average throughput is protected at 8 Mbps and recovers quickly from h3's competition. But transient buffer interactions still cause occasional retransmits. 

This is the tradeoff of statistical multiplexing with QoS. True isolation requires hard slicing — physically or logically separate resources per slice.