import React, { useState, useEffect } from "react";
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import { Color } from "../app/session/[participantId]/page";

export type Input = "sound" | "brightness" | "nothing"
export type Mapping = {id: number, color: Color, input: Input, image_path: string, pos: {x: number, y: number}}

type MappingProps = {
    colors: Color[];
    activeColor: number;
    setActiveColor: React.Dispatch<React.SetStateAction<number>>;
    soundLevel: number;
};

export function MappingList({ colors, activeColor, setActiveColor, soundLevel }: MappingProps) {
    const [mappings, setMappings] = useState<Mapping[]>([]);
    const MAX_MAPPINGS = 4; // when we reach this number, stop rendering + sign
    // const [activeMappingId, setActiveMappingId] = useState<number | null>(null); // this is the id number of the mapping who the user is selecting a color for

    //console.log('sound level', Math.sqrt(soundLevel) * 100)
    // populating mappings
    useEffect(() => {
        const positions = [
            { x: 50, y: 620 }, // pink
            { x: 260, y: 510 }, // blue
            { x: 450, y: 630 }, // green
        ];

        if (!colors || colors.length === 0) return;
        const initialMappings = colors.slice(1, MAX_MAPPINGS ).map((color, index) => ({ // excluding first color, white
          id: index,
          color,
          input: "nothing" as Input,
          image_path: "", // placeholder
          pos: positions[index]
        }));
        setMappings(initialMappings);
      }, []);
       

    // when color button is clicked
    const handleColorButtonClick = (
        event: React.MouseEvent<HTMLElement>,
        id: number
      ) => {
        setActiveColor(id);
    };

    // when color is selected from menu
    const handleColorSelect = (color: Color) => {
        if (activeColor === null) return;
        // change UI

        // setMappings((prev) =>
        //   prev.map((m) =>
        //     m.id === activeColor ? { ...m, color } : m
        //   )
        // );
        // handleClose();
    };

    return (
        <div>
            <div
            style={{
                position: "fixed",
                bottom: "-200px",
                left: "0px",
                zIndex: 10,
                width: "700px",
                height: '500px',
                backgroundImage: "url('/images/palette.png')",
                backgroundSize: "cover",
                backgroundRepeat: "no-repeat",
                backgroundPosition: "center",
                display: "flex",
                flexDirection: "column",
                transform: "rotate(20deg) scale(1.2)",
            }}
            />
            {mappings.map((mapping) => {
                const { id, color, input, image_path, pos } = mapping;
                const isActive = activeColor === id + 1;
                // console.log(mapping)

                return (
                    <div
                        key={id}
                        style={{
                            position: 'absolute',
                            zIndex: 20,
                            top: `${pos.y}px`,
                            left: `${pos.x}px`,
                            //backgroundColor: `rgb(${color.rgb[0]}, ${color.rgb[1]}, ${color.rgb[2]})`,
                            backgroundImage: `url('/images/ellipse_${color.name}.png')`,
                            width: "200px",
                            height: "200px",
                            backgroundSize: "contain",
                            backgroundRepeat: "no-repeat",
                            backgroundPosition: "center",
                            cursor: "pointer",
                            clipPath: "circle(50% at 50% 50%)",
                            opacity: isActive ? 1 : 0.6,
                            transition: "opacity 0.2s ease-in-out",
                        }}
                        onClick={(e) => setActiveColor(id+1)}
                    >
                        {id === 0 && (
                            <div
                            style={{
                                position: "absolute",
                                zIndex: 30,
                                bottom: "60px",
                                left: "60px",
                                width: `${soundLevel}%`,
                                height: "20px",
                                background: "gray",
                                borderRadius: 4,
                                // transition: "width 0.1s linear",
                                pointerEvents: "none",
                            }}
                            />
                        )}
                    </div>
                )
            })}
        </div>
    )
}