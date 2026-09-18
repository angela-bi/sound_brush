import React from "react";
import { useEffect, useState } from "react";
import { Handle, Position } from "@xyflow/react";

export function BrushSettingNode({ id }: { id: string }) {

    return (
    <div
        style={{
        width: 100,
        height: 50,
        border: "0.5px solid gray",
        borderRadius: 8,
        background: "white",
        display: "flex",
        // alignItems: "flex-end",
        flexDirection: "column",
        justifyContent: "left",
        padding: 10,
        color: "white",
        fontSize: 10,
        }}
    >
        <div style={{color: "black"}}>Brush Size</div>
        {/* <div
            style={{
                width: `${height}%`,
                height: "40%",
                background: "gray",
                borderRadius: 4,
                transition: "height 0.3s linear fade",
            }}
        /> */}
        {/* <span style={{ position: "absolute", top: 4 }}>{id}</span> */}

        {/* Connection handles */}
        <Handle type="target" position={Position.Left} />
        <Handle type="source" position={Position.Right} />
    </div>
    );
    }
